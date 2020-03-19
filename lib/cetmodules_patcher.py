
import sys
import os
import re

def fixrootlib(x):
    part = x.group(1)
    for lib in ("GenVector", "Core", "Imt", "RIO", "Net", "Hist", "Graf", "Graf3d", "Gpad", "ROOTVecOps", "Tree", "TreePlayer", "Rint", "Postscript", "Matrix", "Physics", "MathCore", "Thread", "MultiProc", "ROOTDataFrame"):
         if lib.lower() == part.lower():
              return 'ROOT::%s' % lib
    return 'ROOT::%s' % part.lower().capitalize()
        
def cetmodules_dir_patcher(dir, proj, vers, debug=False):
    for rt, drs, fnames in os.walk(dir):
        if "CMakeLists.txt" in fnames:
            cetmodules_file_patcher(rt + "/CMakeLists.txt", rt == dir, proj, vers, debug)
        for fname in fnames:
            if fname.endswith(".cmake"):
                cetmodules_file_patcher("%s/%s" % (rt, fname), rt == dir, proj, vers)

cmake_cet_ver_re = re.compile(r"SET\s*\(\s*CETBUILDTOOLS_VERSION\s*\$ENV{CETBUILDTOOLS_VERSION}\s*\)")
cmake_min_re = re.compile(r"cmake_minimum_required\s*\(\s*[VERSION ]*(\d*\.\d*).*\)")
cmake_project_re = re.compile(r"project\(\s*(\S*)(.*)\)")
cmake_ups_boost_re  = re.compile(r"find_ups_boost\(.*\)")
cmake_ups_root_re  = re.compile(r"find_ups_root\(.*\)")
cmake_find_ups_re  = re.compile(r"find_ups_product\(\s*(\S*).*\)")
cmake_find_cetbuild_re = re.compile(r"find_package\s*\(\s*(cetbuildtools.*)\)")
cmake_find_lib_paths_re = re.compile("cet_find_library\((.*) PATHS ENV.*NO_DEFAULT_PATH")
boost_re = re.compile(r"\$\{BOOST_(\w*)_LIBRARY\}")
root_re = re.compile(r"\$\{ROOT_(\w*)_LIBRARY\}")
tbb_re = re.compile(r"\$\{TBB}")
dir_re = re.compile(r"\$\{\([A-Z_]\)_DIR\}")
drop_re = re.compile(r"(_cet_check\()|(include\(UseCPack\))|(add_subdirectory\(\s*ups\s*\))|(cet_have_qual\()|(check_ups_version\()")
cmake_config_re = re.compile(r"cet_cmake_config\(")
cmake_inc_cme_re = re.compile(r"include\(CetCMakeEnv\)")
cmake_inc_ad_re = re.compile(r"include\(ArtDictionary\)")

def fake_check_ups_version(line, fout):
    p0 = line.find("PRODUCT_MATCHES_VAR ") + 20
    p1 = line.find(")")
    fout.write("set( %s True )\n" % line[p0:p1] )

def cetmodules_file_patcher(fname, toplevel=True, proj='foo', vers='1.0', debug=False):
    sys.stderr.write("Patching file '%s'\n" % fname)
    fin = open(fname,"r")
    fout = open(fname+".new", "w")
    need_cmake_min = toplevel
    need_project = toplevel
    drop_til_close = False
    saw_cmake_config = False
    saw_cetmodules = False
    saw_canvas_root_io = False

    for line in fin:

        if debug:
             sys.stderr.write("line: %s" % line)

        line = line.rstrip()
        if drop_til_close:
            if line.find(")") > 0:
                drop_til_close = False
            if line.find("PRODUCT_MATCHES_VAR") > 0:
                fake_check_ups_version(line, fout)
            continue
        line = dir_re.sub(lambda x:'${%s_DIR}' % x.group(1).lower(), line)
        line = boost_re.sub(lambda x:'Boost::%s' % x.group(1).lower(), line)
        line = root_re.sub(fixrootlib, line)
        line = tbb_re.sub('TBB:tbb', line)

        mat = cmake_inc_ad_re.search(line)
        if mat and not saw_canvas_root_io:
            if debug:
                 sys.stderr.write("inc_ad without canvas_root_io\n")
            fout.write("find_package(canvas-root-io)\n")
            fout.write(line + "\n")
            continue
    
        mat = cmake_find_cetbuild_re.search(line)
        if mat:
            if debug:
                 sys.stderr.write("cetbuild\n")
            sys.stderr.write("fixing cetbuild in: %s\n" % line)
            fout.write("find_package(cetmodules)\n")
            saw_cetmodules = True
            continue

        mat = cmake_inc_cme_re.search(line)
        if mat and not saw_cetmodules:
            if debug:
                 sys.stderr.write("cetbuild_re\n")
            fout.write("find_package(cetmodules)\n")
            saw_cetmodules = True
            fout.write(line + "\n")
            continue

        mat = cmake_config_re.search(line)
        if mat:
            if debug:
                 sys.stderr.write("config_re\n")
            saw_cmake_config = True

        # fool cetbuildtools version checks
        mat = cmake_cet_ver_re.search(line)
        if mat:
            if debug:
                 sys.stderr.write("cetver_re\n")
            fout.write("SET ( CETBUILDTOOLS_VERSION 1 )\n")
            continue

        mat = drop_re.search(line)
        if mat: 
            if debug:
                 sys.stderr.write("drop_re\n")
            if line.find(")") < 0:
                drop_til_close = True
            if line.find("PRODUCT_MATCHES_VAR") > 0:
                fake_check_ups_version(line, fout)
            continue

        mat = cmake_min_re.search(line)
        if mat:
            if debug:
                 sys.stderr.write("min_re\n")
            fout.write( "cmake_minimum_required(VERSION %s)\n" % str(max(float(mat.group(1)), 3.11)))
            need_cmake_min = False
            continue
        
        mat = cmake_find_lib_paths_re.search(line)
        if mat:
            if debug:
                 sys.stderr.write("find_lib_paths_re\n")
            fout.write("cet_find_library(%s)\n" % mat.group(1).replace("_ups",""))
            continue

        mat = cmake_project_re.search(line)
        if mat:
            if debug:
                 sys.stderr.write("project_re\n")
            if mat.group(2).find("VERSION") >= 0:
                fout.write( line + "\n" )
            else:
                fout.write( "project(%s VERSION %s LANGUAGES CXX)\n" % (mat.group(1),vers))
            need_project = False
            continue

        mat = cmake_ups_root_re.search(line)
        if mat:
            if debug:
                 sys.stderr.write("ups_root_re\n")
            if need_cmake_min:
               fout.write("cmake_minimum_required(VERSION 3.11)\n")
               need_cmake_min = False
            if need_project:
               fout.write("project( %s VERSION %s LANGUAGES CXX )" % (proj,vers))
               need_project = False
              
            fout.write("find_package(ROOT COMPONENTS GenVector Core Imt RIO Net Hist Graf Graf3d Gpad ROOTVecOps Tree TreePlayer Rint Postscript Matrix Physics MathCore Thread MultiProc ROOTDataFrame)\n")
            continue

        mat = cmake_ups_boost_re.search(line)
        if mat:
            if debug:
                 sys.stderr.write("ups_boost_re\n")
            if need_cmake_min:
               fout.write("cmake_minimum_required(VERSION 3.11)\n")
               need_cmake_min = False
            if need_project:
               fout.write("project( %s VERSION %s LANGUAGES CXX )" % (proj,vers))
               need_project = False
            fout.write("find_package(Boost COMPONENTS system filesystem program_options date_time graph thread regex random)")
            continue

        mat = cmake_find_ups_re.search(line)
        if mat:
            if debug:
                 sys.stderr.write("ups_find_ups_re\n")
            if need_cmake_min:
               fout.write("cmake_minimum_required(VERSION 3.11)\n")
               need_cmake_min = False
            if need_project:
               fout.write("project( %s VERSION %s LANGUAGES CXX )" % (proj,vers))
               need_project = False

            newname = mat.group(1)

            if newname == 'cetbuildtools':
                newname = 'cetmodules'

            if newname == 'canvas_root_io':
                saw_canvas_root_io = True

            newname = newname.replace("_","-")
            if newname.find("lib") == 0:
               newname = newname[3:]

            if newname in ("clhep",):
               newname = newname.upper()

            if newname in ("sqlite3",):
               newname = newname.capitalize().strip("0123456789")

            if newname == "ifdhc":
               fout.write("cet_find_simple_package( ifdhc INCPATH_SUFFIXES inc INCPATH_VAR IFDHC_INC )\n")
            elif newname in ("wda", "ifbeam", "nucondb", "cetlib", "cetlib-except", "ifdhc"):
               fout.write("cet_find_simple_package( %s INCPATH_VAR %s_INC )\n" % (newname, newname.upper()))
            else:
                fout.write("find_package( %s )\n" % newname )
            continue

        fout.write(line+"\n")

    if toplevel and not saw_cmake_config:
        fout.write("cet_cmake_config()\n")

    fin.close()
    fout.close()
    if os.path.exists(fname+'.bak'):
        os.unlink(fname+'.bak')
    os.link(fname, fname+'.bak')
    os.rename(fname+'.new', fname)

if __name__ == '__main__':
    debug = False
    if sys.argv[1] == '-d':
        sys.argv = [sys.argv[0]] + sys.argv[2:]
        debug = True

    if len(sys.argv) != 4 or not os.path.isdir(sys.argv[1]):
        sys.stderr.write("usage: %s directory package-name package-version\n" % sys.argv[0])
        sys.exit(1)
    cetmodules_dir_patcher(sys.argv[1], sys.argv[2],sys.argv[3], debug=debug)
