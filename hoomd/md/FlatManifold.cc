// Copyright (c) 2009-2020 The Regents of the University of Michigan
// This file is part of the HOOMD-blue project, released under the BSD 3-Clause License.


// Maintainer: pschoenhoefer

#include "FlatManifold.h"

namespace py = pybind11;

using namespace std;

/*! \file FlatManifold.cc
    \brief Contains code for the FlatManifold class
*/

/*!
    \param r radius of the sphere
    \param P position of the sphere
*/
FlatManifold::FlatManifold(std::shared_ptr<SystemDefinition> sysdef,
                               std::string surf,
                               Scalar shift)
  : Manifold(sysdef), m_shift(shift) 
       {
    m_exec_conf->msg->notice(5) << "Constructing FlatManifold " << surf << endl;

    if( surf == "XY" || surf == "YX" ){ 
	xy = true;
	m_surf = 4;
    }
    else
    { 
	if( surf == "XZ" || surf == "ZX" ){ 
		xz = true;
		m_surf = 5;
	}
        else
        { 
	   if( surf == "YZ" || surf == "ZY" ){ 
		yz = true;
		m_surf = 6;
	  }
        }
    }

 }

FlatManifold::~FlatManifold() 
       {
    m_exec_conf->msg->notice(5) << "Destroying FlatManifold" << endl;
       }

        //! Return the value of the implicit surface function of the sphere.
        /*! \param point The position to evaluate the function.
        */
Scalar FlatManifold::implicit_function(Scalar3 point)
       {
	       if(xy)
		   return (point.z-m_shift);
	       else{
		   if(xz){
			return (point.y-m_shift);
		   }else{
			return (point.x-m_shift);
		   }
	       }
       }

       //! Return the gradient of the constraint.
       /*! \param point The location to evaluate the gradient.
       */
Scalar3 FlatManifold::derivative(Scalar3 point)
       {
	       if(xy)
		   return make_scalar3(0,0,1);
	       else{
		   if(xz){
			return make_scalar3(0,1,0);
		   }else{
			return make_scalar3(1,0,0);
		   }
	       }
       }


//! Exports the FlatManifold class to python
void export_FlatManifold(pybind11::module& m)
    {
    py::class_< FlatManifold, std::shared_ptr<FlatManifold> >(m, "FlatManifold", py::base<Manifold>())
    .def(py::init< std::shared_ptr<SystemDefinition>,std::string, Scalar >())
    .def("implicit_function", &FlatManifold::implicit_function)
    .def("derivative", &FlatManifold::derivative)
    ;
    }
